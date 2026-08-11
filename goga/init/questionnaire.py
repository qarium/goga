from __future__ import annotations

import click

from .answers import GogaConfigAnswers, InitAnswers

_IMAGE_MAP: dict[str, list[str]] = {
    "python": [
        "qarium/goga-python-3.10:1.1",
        "qarium/goga-python-3.11:1.1",
        "qarium/goga-python-3.12:1.1",
        "qarium/goga-python-3.13:1.1",
        "qarium/goga-python-3.14:1.1",
    ],
    "golang": [
        "qarium/goga-golang-1.23:1.1",
        "qarium/goga-golang-1.24:1.1",
        "qarium/goga-golang-1.25:1.1",
        "qarium/goga-golang-1.26:1.1",
    ],
    "javascript": [
        "qarium/goga-node-22:1.1",
        "qarium/goga-node-24:1.1",
    ],
    "kotlin": [
        "qarium/goga-kotlin-2.0:1.1",
        "qarium/goga-kotlin-2.1:1.1",
        "qarium/goga-kotlin-2.2:1.1",
        "qarium/goga-kotlin-2.3:1.1",
    ],
    "swift": [
        "qarium/goga-swift-6.0:1.1",
        "qarium/goga-swift-6.1:1.1",
        "qarium/goga-swift-6.2:1.1",
    ],
}

_LANGUAGES = ["python", "golang", "kotlin", "swift", "javascript"]

_AGENT_ENV_MAP: dict[str, list[str]] = {
    "claude": [
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_MODEL",
    ],
    "codex": [
        "CODEX_MODEL",
    ],
    "cursor": [
        "CURSOR_MODEL",
    ],
    "opencode": [
        "OPENCODE_MODEL",
        "OPENCODE_VARIANT",
    ],
    "qwen": [
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
    ],
}


def _collect_agent_env(agent: str | None) -> dict | None:
    """Collect environment variables for an agent.

    Proposes keys from `_AGENT_ENV_MAP` for the given agent, then optionally
    collects arbitrary KEY=VALUE pairs. Returns None when nothing is collected.
    A None agent (no agent configured) skips the suggested-keys block and only
    offers arbitrary KEY=VALUE pairs.
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

    def ask_goga_config(self) -> GogaConfigAnswers:
        """Run questionnaire for .goga/config.yml creation.

        Orchestrates the per-field ask_* survey methods in order and assembles
        the results into a GogaConfigAnswers.

        Returns:
            GogaConfigAnswers with all collected goga config fields.
        """
        click.echo("Collecting .goga/config.yml settings...\n")

        language = self.ask_language()

        usages_prefill, annotations_prefill = self.ask_base_convention()
        codemanifest_usages = self.ask_codemanifest_usages(usages_prefill)
        codemanifest_annotations = self.ask_codemanifest_annotations(annotations_prefill)

        agent = self.ask_agent()

        # The Dockerfile decision drives the image semantics: with a Dockerfile
        # the image is BUILT from it (needs its own name + a FROM base), without
        # a Dockerfile a pre-built image is pulled.
        dockerfile_path = self.ask_dockerfile_path()
        if dockerfile_path is not None:
            dockerfile_base_image = self.ask_base_image(language)
            image = self.ask_image_name(language)
        else:
            dockerfile_base_image = None
            image = self.ask_image(language)

        env = self.ask_env(agent)
        pipeline_agent = self.ask_pipeline_agent()
        pipeline_env = self.ask_pipeline_env(pipeline_agent)

        return GogaConfigAnswers(
            language=language,
            agent=agent,
            image=image,
            pipeline_agent=pipeline_agent,
            pipeline_env=pipeline_env,
            env=env,
            dockerfile_path=dockerfile_path,
            dockerfile_base_image=dockerfile_base_image,
            codemanifest_usages=codemanifest_usages,
            codemanifest_annotations=codemanifest_annotations,
        )

    def ask_language(self) -> str:
        """Survey the primary programming language.

        Returns:
            One of python, golang, kotlin, swift, javascript.
        """
        click.echo("--- Project Language ---")
        click.echo("Select the primary programming language for your project.")

        return click.prompt(
            "Language",
            type=click.Choice(_LANGUAGES),
        )

    def ask_base_convention(self) -> tuple[dict | None, str | None]:
        """Offer to download the base convention for the selected language.

        Acceptance pre-fills both codemanifest fields:
        - codemanifest_usages with {"conventions": ".goga/usages/conventions.md"}
        - codemanifest_annotations with the conventions directive text.

        Returns:
            (codemanifest_usages, codemanifest_annotations) pre-fill pair;
            (None, None) when the user declines.
        """
        click.echo("\n--- Base Convention ---")
        click.echo("Download the default code conventions for your language?")

        if click.confirm("Download base convention"):
            return (
                {"conventions": ".goga/usages/conventions.md"},
                "Use `conventions` for code writing rules and testing.",
            )

        return None, None

    def ask_codemanifest_usages(self, prefill: dict | None = None) -> dict | None:
        """Collect optional additional codemanifest usages onto `prefill`.

        Args:
            prefill: existing usages (e.g. the base convention entry) to extend.

        Returns:
            Merged usages dict, or None when neither prefill nor input exists.
        """
        codemanifest_usages = prefill
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

        return codemanifest_usages

    def ask_codemanifest_annotations(self, prefill: str | None = None) -> str | None:
        """Collect optional custom codemanifest annotations appended to `prefill`.

        Args:
            prefill: existing annotations text to append to.

        Returns:
            Merged annotations string, or None when neither exists.
        """
        codemanifest_annotations = prefill
        click.echo("\n--- Codemanifest Annotations ---")
        click.echo("Add custom codemanifest annotations (global directives for AI agent).")

        if click.confirm("Add codemanifest annotations?", default=False):
            custom = click.prompt("Annotations")

            if codemanifest_annotations is not None:
                codemanifest_annotations = codemanifest_annotations + "\n" + custom
            else:
                codemanifest_annotations = custom

        return codemanifest_annotations

    def ask_agent(self) -> str | None:
        """Survey the AI agent that builds the implementation.

        Optional: by default no agent is configured. The user must opt in via a
        confirm gate, then select from (claude, codex). Declining returns None —
        the agent is omitted from the generated config.

        Returns:
            One of claude, codex; None when the user declines to configure an agent.
        """
        click.echo("\n--- AI Agent ---")
        click.echo("Select the AI agent that will build implementation.")

        if not click.confirm("Configure a build agent?", default=False):
            return None

        return click.prompt(
            "Agent",
            type=click.Choice(["claude", "codex"]),
        )

    def ask_image(self, language: str) -> str:
        """Survey the pre-built Docker image to PULL (no-Dockerfile case).

        Used when the user does NOT create a custom Dockerfile: build/pipeline
        pull this pre-built image. Displays language-specific hints from
        `image_defaults` and defaults to the last entry; accepts free-form input.

        Args:
            language: the selected project language (drives the hint list).

        Returns:
            Docker image name. Captures the top-level image field (NOT build.image).
        """
        return self._prompt_language_image(
            language,
            section="Docker Image",
            intro="Select the pre-built Docker image to use (pulled at build/pipeline time).",
            prompt_label="Docker image",
        )

    def ask_base_image(self, language: str) -> str:
        """Survey the BASE image for the Dockerfile FROM (Dockerfile case).

        Used when the user creates a custom Dockerfile: this image is the FROM
        baseline the built image extends. Displays language-specific hints from
        `image_defaults` and defaults to the last entry; accepts free-form input.

        Args:
            language: the selected project language (drives the hint list).

        Returns:
            Base Docker image name. Written as the Dockerfile FROM line; never
            emitted to config.yml.
        """
        return self._prompt_language_image(
            language,
            section="Dockerfile Base Image",
            intro="Select the base image for the Dockerfile (the FROM line).",
            prompt_label="Base image (FROM)",
        )

    def ask_image_name(self, language: str) -> str:
        """Survey the NAME (tag) for the image built from the Dockerfile.

        Used when the user creates a custom Dockerfile: `goga build` runs
        `docker build -t <image>`, so the built image needs its own name,
        distinct from the FROM base. Free-form input with a language-derived
        placeholder default.

        Args:
            language: the selected project language (drives the default placeholder).

        Returns:
            Docker image name. Captures the top-level image field (NOT build.image).
        """
        click.echo("\n--- Built Image Name ---")
        click.echo("Name for the docker image built from the Dockerfile (the top-level image field).")

        return click.prompt("Built image name", default=f"{language}-image:latest")

    def _prompt_language_image(
        self,
        language: str,
        *,
        section: str,
        intro: str,
        prompt_label: str,
    ) -> str:
        """Prompt for a Docker image, hinting language-specific defaults.

        Lists the predefined images for `language` (from `_IMAGE_MAP`) and
        defaults to the last entry; accepts free-form input. When the language
        has no predefined images, no hints are shown and no default is offered.

        Args:
            language: the selected project language (drives the hint list).
            section: the `---` section header text.
            intro: the explanatory line under the header.
            prompt_label: the click.prompt label.

        Returns:
            Docker image name. Defaults to the last hint when hints exist.
        """
        click.echo(f"\n--- {section} ---")
        click.echo(intro)
        images = _IMAGE_MAP.get(language)

        if images is not None:
            click.echo("Available images:")

            for img in images:
                click.echo(f"  - {img}")

            return click.prompt(prompt_label, default=images[-1])
        return click.prompt(prompt_label)

    def ask_dockerfile_path(self) -> str | None:
        """Optionally survey a custom Dockerfile path.

        Returns:
            Dockerfile path (default ".goga/Dockerfile"), or None to skip.
        """
        click.echo("\n--- Custom Dockerfile ---")
        click.echo("Create a custom Dockerfile for the build implementation?")

        if click.confirm("Create Dockerfile?", default=False):
            return click.prompt("Dockerfile path", default=".goga/Dockerfile")

        return None

    def ask_env(self, agent: str | None) -> dict | None:
        """Survey build task_executor environment variables for `agent`.

        Args:
            agent: the selected build agent (drives suggested env keys); None when
                no agent is configured.

        Returns:
            Env dict collected via `_collect_agent_env`, or None.
        """
        click.echo("\n--- Environment Variables ---")
        click.echo("Configure environment variables for the build implementation.")

        return _collect_agent_env(agent)

    def ask_pipeline_agent(self) -> str | None:
        """Survey the pipeline agent.

        Optional: by default no pipeline agent is configured. The user must opt
        in via a confirm gate, then select from (claude, codex). Declining
        returns None — the pipeline agent is omitted from the generated config.
        The pipeline agent does NOT inherit the build `agent`.

        Returns:
            One of claude, codex; None when the user declines to configure an agent.
        """
        click.echo("\n--- Pipeline Agent ---")
        click.echo("Select the AI agent that will run pipelines (afm client.command).")

        if not click.confirm("Configure a pipeline agent?", default=False):
            return None

        return click.prompt(
            "Pipeline agent",
            type=click.Choice(["claude", "codex"]),
        )

    def ask_pipeline_env(self, pipeline_agent: str | None) -> dict | None:
        """Survey pipeline environment variables for `pipeline_agent`.

        Args:
            pipeline_agent: the selected pipeline agent (drives suggested env keys);
                None when no agent is configured.

        Returns:
            Env dict collected via `_collect_agent_env`, or None.
        """
        click.echo("\n--- Pipeline Environment Variables ---")
        click.echo("Configure environment variables for the pipeline implementation.")

        return _collect_agent_env(pipeline_agent)

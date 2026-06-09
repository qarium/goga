from __future__ import annotations

import urllib.request
from pathlib import Path

import yaml


class _LiteralStr(str):
    """String subclass that serializes as YAML literal block scalar (|)."""


def _represent_literal_str(dumper: yaml.Dumper, data: _LiteralStr) -> yaml.ScalarNode:
    text = data if data.endswith("\n") else data + "\n"
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style="|")


yaml.add_representer(_LiteralStr, _represent_literal_str)

from .answers import GogaConfigAnswers, InitAnswers

_CONVENTION_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/qarium/goga-lang-conventions/"
    "refs/heads/0.0.x/{language}/project.md"
)


class FileGenerator:
    """Generates project files from user answers."""

    def __init__(self) -> None:
        self._base_dir: Path = Path()

    def generate(self, answers: InitAnswers) -> None:
        """Create all files based on answers.

        If dockerfile_path is set — creates Dockerfile, then generates config.yml.
        """
        config = answers.goga_config

        if config.dockerfile_path is not None:
            dockerfile_content = f"FROM {config.image}\n"
            dockerfile = self._base_dir / config.dockerfile_path
            dockerfile.parent.mkdir(parents=True, exist_ok=True)
            dockerfile.write_text(dockerfile_content, encoding="utf-8")

        self.generate_goga_config(config)

    def generate_goga_config(self, config: GogaConfigAnswers) -> None:
        """Create .goga/config.yml from GogaConfigAnswers.

        Downloads convention if codemanifest_usages contains 'conventions'.
        Raises on download failure — config.yml is NOT created.
        """
        usages = config.codemanifest_usages

        if usages is not None and "conventions" in usages:
            url = _CONVENTION_URL_TEMPLATE.format(language=config.language)

            try:
                with urllib.request.urlopen(url, timeout=30) as response:
                    content = response.read().decode("utf-8")
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to download convention from {url}: {exc}"
                ) from exc

            usages_dir = self._base_dir / ".goga" / "usages"
            usages_dir.mkdir(parents=True, exist_ok=True)
            (usages_dir / "conventions.md").write_text(content, encoding="utf-8")

        goga_dir = self._base_dir / ".goga"
        goga_dir.mkdir(parents=True, exist_ok=True)

        data: dict = {
            "language": config.language,
            "build": {
                "image": config.image,
                "task_executor": {
                    "agent": config.agent,
                },
            },
        }

        if config.env:
            data["build"]["task_executor"]["env"] = config.env

        if config.codemanifest_usages is not None or config.codemanifest_annotations is not None:
            codemanifest: dict = {}
            if config.codemanifest_usages:
                codemanifest["usages"] = config.codemanifest_usages
            if config.codemanifest_annotations is not None:
                codemanifest["annotations"] = _LiteralStr(
                    config.codemanifest_annotations
                )
            data["codemanifest"] = codemanifest

        with (goga_dir / "config.yml").open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

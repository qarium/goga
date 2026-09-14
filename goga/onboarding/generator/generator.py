"""The artifact generator of the onboarding session.

The entities declared in the cell CODEMANIFEST with ``location: generator.py``:
the generator ``FileGenerator`` and the report record ``CreatedFile``. The
generator writes every artifact of the session from the committed answer
space and the committed tool contributions — the project config, the
Dockerfile, the base conventions download, and the tool config files — and
reports the created files with attribution. An existing .goga/config.yml is
never rewritten: whoever created it first wins.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

from ..participation import ToolContribution
from ..questions import SessionAnswers

logger = logging.getLogger(__name__)

_CONVENTION_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/qarium/goga-lang-conventions/refs/heads/0.0.x/{language}/project.md"
)

_CONVENTIONS_PATH = Path(".goga") / "usages" / "conventions.md"
_CONFIG_PATH = Path(".goga") / "config.yml"


class _LiteralStr(str):
    """String subclass that serializes as YAML literal block scalar (|)."""


def _represent_literal_str(dumper: yaml.Dumper, data: _LiteralStr) -> yaml.ScalarNode:
    text = data if data.endswith("\n") else data + "\n"
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style="|")


yaml.add_representer(_LiteralStr, _represent_literal_str)


@dataclass(frozen=True, kw_only=True)
class CreatedFile:
    """One entry of the final file report — a created file with its attribution.

    Attributes:
        path: The created file path relative to the project root.
        tool: The tool identity of the file; None for an engine file.
    """

    path: str
    tool: str | None


def _executor_block(section: dict) -> dict | None:
    """Assemble a build.task_executor / pipeline content dict.

    Keys are emitted in field order (``agent``, then ``env``). The block is
    omitted entirely when it carries no content (no agent and no/empty env).

    Args:
        section: The snapshot section carrying the ``agent`` and ``env``
            answers of one executor.

    Returns:
        A dict with `agent` and/or `env` keys (in that order), or None when
        the block carries no content — signalling the caller to omit it.
    """
    block: dict = {}

    agent = section.get("agent")
    if agent is not None:
        block["agent"] = agent

    env = section.get("env")
    if env:
        block["env"] = env

    return block or None


def _codemanifest_block(section: dict) -> dict | None:
    """Assemble the optional codemanifest block, or None when it has no content.

    Args:
        section: The snapshot codemanifest section carrying ``usages`` and
            ``annotations``.

    Returns:
        A codemanifest dict with `usages` and/or `annotations` keys, or None
        when neither is present — signalling the caller to omit the block.
    """
    usages = section.get("usages")
    annotations = section.get("annotations")

    if not usages and annotations is None:
        return None

    block: dict = {}

    if usages:
        block["usages"] = usages

    if annotations is not None:
        block["annotations"] = _LiteralStr(annotations)

    return block


def _conventions_requested(snapshot: dict) -> bool:
    """Check whether the snapshot asks for the base conventions download.

    Args:
        snapshot: The committed answer snapshot.

    Returns:
        True when the codemanifest usages carry the ``conventions`` entry —
        the single condition of the download and its report entry.
    """
    codemanifest = snapshot.get("codemanifest")
    usages = codemanifest.get("usages") if isinstance(codemanifest, dict) else None

    return isinstance(usages, dict) and "conventions" in usages


def _build_config_document(snapshot: dict) -> dict:
    """Assemble the config.yml mapping from the answer snapshot.

    Only the mapped fields of the snapshot enter the document — every other
    top-level key (the confirm gates, the tool sections) never reaches the
    config. Field order: language, image, dockerfile, build, pipeline,
    codemanifest, tools, usages; optional fields and empty blocks are
    omitted.

    Args:
        snapshot: The committed answer snapshot.

    Returns:
        The ordered mapping to serialize into .goga/config.yml.
    """
    docker_image = snapshot.get("docker_image") or {}

    data: dict = {"language": snapshot["language"]}

    image = docker_image.get("image")
    if image is not None:
        data["image"] = image

    # The dockerfile field appears only when the Dockerfile was written —
    # both the path and the base image must be present.
    dockerfile = docker_image.get("dockerfile")
    if dockerfile is not None and docker_image.get("base_image") is not None:
        data["dockerfile"] = dockerfile

    build_block = _executor_block(snapshot.get("build") or {})
    if build_block is not None:
        data["build"] = {"task_executor": build_block}

    pipeline_block = _executor_block(snapshot.get("pipeline") or {})
    if pipeline_block is not None:
        data["pipeline"] = pipeline_block

    codemanifest_block = _codemanifest_block(snapshot.get("codemanifest") or {})
    if codemanifest_block is not None:
        data["codemanifest"] = codemanifest_block

    tools = snapshot.get("tools")
    if tools:
        data["tools"] = tools

    usages = snapshot.get("usages")
    if usages:
        data["usages"] = usages

    return data


def _write_tool_configs(contributions: list[ToolContribution]) -> list[CreatedFile]:
    """Write every buffered tool config file and collect the report entries.

    Args:
        contributions: The committed contributions, in enumeration order.

    Returns:
        The created tool files with attribution, in write order — one entry
        per buffered write; a repeated file name replaces the file.
    """
    files: list[CreatedFile] = []

    for contribution in contributions:
        tool_dir = Path(".goga") / "tools" / contribution.tool

        for file, data in contribution.files:
            tool_dir.mkdir(parents=True, exist_ok=True)
            path = tool_dir / file

            with path.open("w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            files.append(CreatedFile(path=str(path), tool=contribution.tool))

    return files


class FileGenerator:
    """The artifact generator of the session — every write of the run.

    The generator consumes the committed answer space and the committed tool
    contributions: the Dockerfile from the base-image answer, the project
    config from the snapshot, the base conventions download behind the
    codemanifest usages entry, and the tool config files buffered by the
    tools. It is the single write path of the session — a tool never writes
    its config files itself — and the report it returns is the single source
    of the final file list.

    Requirements:
        an existing .goga/config.yml is never rewritten — whoever created
        it first wins; the guarantee lives here, not only at the caller.
    """

    def __init__(self) -> None:
        """Create the generator."""

    def generate(self, answers: SessionAnswers, contributions: list[ToolContribution]) -> list[CreatedFile]:
        """Generate every artifact of the session and report the created files.

        Args:
            answers: The committed answer space of the session.
            contributions: The committed contributions, in enumeration order.

        Returns:
            The created files with attribution — an engine file carries a
            None tool, a tool file carries the tool identity — in generation
            order: the Dockerfile, the downloaded conventions.md, the config,
            then the tool files.

        Raises:
            ValueError: When the snapshot carries no language — the single
                required-field check of the session.
            RuntimeError: When the conventions download fails — the config
                is then not created.
        """
        files: list[CreatedFile] = []

        if not _CONFIG_PATH.is_file():
            snapshot = answers.snapshot()

            docker_image = snapshot.get("docker_image") or {}
            dockerfile = docker_image.get("dockerfile")
            base_image = docker_image.get("base_image")

            if dockerfile is not None and base_image is not None:
                path = Path(dockerfile)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"FROM {base_image}\n", encoding="utf-8")
                files.append(CreatedFile(path=dockerfile, tool=None))

            self.generate_goga_config(answers)

            if _conventions_requested(snapshot):
                files.append(CreatedFile(path=str(_CONVENTIONS_PATH), tool=None))

            files.append(CreatedFile(path=str(_CONFIG_PATH), tool=None))

        files.extend(_write_tool_configs(contributions))

        return files

    def generate_goga_config(self, answers: SessionAnswers) -> None:
        """Generate .goga/config.yml from the answer snapshot.

        Downloads the base conventions per the `lang_conventions` practice
        when the codemanifest usages carry the conventions entry — the file
        is written before the config; a download failure is a clean error
        with the URL and the cause, and the config is then not created.

        Args:
            answers: The committed answer space.

        Raises:
            ValueError: When the snapshot carries no language — the single
                required-field check.
            RuntimeError: When the conventions download fails; config.yml is
                NOT created.
        """
        snapshot = answers.snapshot()

        language = snapshot.get("language")
        if not language:
            raise ValueError("the survey must record the language field — the config cannot be generated without it")

        if _conventions_requested(snapshot):
            url = _CONVENTION_URL_TEMPLATE.format(language=language)

            logger.info("downloading convention", extra={"language": language, "url": url})
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                content = response.text
            except requests.RequestException as exc:
                logger.error("convention download failed", extra={"url": url, "error": str(exc)})
                raise RuntimeError(f"Failed to download convention from {url}: {exc}") from exc

            _CONVENTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _CONVENTIONS_PATH.write_text(content, encoding="utf-8")

        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

        data = _build_config_document(snapshot)

        with _CONFIG_PATH.open("w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def generate_tool_configs(self, contributions: list[ToolContribution]) -> None:
        """Generate the tool config files from the committed contributions.

        The buffered data is written verbatim, without interpretation — the
        engine is the single write path of the tool configs.

        Args:
            contributions: The committed contributions, in enumeration order.
        """
        _write_tool_configs(contributions)

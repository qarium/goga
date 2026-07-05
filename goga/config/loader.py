from pathlib import Path

import yaml

from .config import (
    BuildConfig,
    CodemanifestConfig,
    Config,
    PipelineConfig,
    TaskExecutorConfig,
)


def _parse_task_executor(task_executor_data: dict) -> TaskExecutorConfig:
    """Parse and validate task_executor section into a TaskExecutorConfig instance."""
    agent = task_executor_data.get("agent")
    if not isinstance(agent, str) or not agent.strip():
        raise ValueError("build.task_executor.agent is required in .goga/config.yml")

    env = task_executor_data.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("build.task_executor.env must be a mapping in .goga/config.yml")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("build.task_executor.env must have string keys and values")

    return TaskExecutorConfig(agent=agent.strip(), env=dict(env))


def _parse_pipeline(pipeline_data: dict) -> PipelineConfig:
    """Parse and validate the pipeline section into a PipelineConfig instance."""
    agent = pipeline_data.get("agent")
    if not isinstance(agent, str) or not agent.strip():
        raise ValueError("pipeline.agent is required in .goga/config.yml")

    env = pipeline_data.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("pipeline.env must be a mapping in .goga/config.yml")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("pipeline.env must have string keys and values")

    return PipelineConfig(agent=agent.strip(), env=dict(env))


def _parse_language(data: dict) -> str:
    """Extract and validate the language field from YAML data."""
    try:
        lang = data["language"]
    except KeyError as err:
        raise KeyError("language is required in .goga/config.yml") from err

    if not isinstance(lang, str) or not lang.strip():
        raise ValueError("language must be a non-empty string in .goga/config.yml")

    return lang.strip()


def _parse_image(data: dict) -> str | None:
    """Extract the optional top-level image field; None is a valid value."""
    image = data.get("image")
    if image is not None and not isinstance(image, str):
        raise ValueError("image must be a string in .goga/config.yml")
    return image


def _parse_codemanifest(data: dict) -> CodemanifestConfig | None:
    """Parse optional codemanifest section from YAML data."""
    codemanifest_data = data.get("codemanifest")
    if codemanifest_data is None:
        return None
    if not isinstance(codemanifest_data, dict):
        raise ValueError("'codemanifest' must be a mapping in .goga/config.yml")

    usages = codemanifest_data.get("usages", {})
    if not isinstance(usages, dict):
        raise ValueError("codemanifest.usages must be a mapping")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in usages.items()):
        raise ValueError("codemanifest.usages must have string keys and values")

    annotations = codemanifest_data.get("annotations")
    if annotations is not None and not isinstance(annotations, str):
        raise ValueError("codemanifest.annotations must be a string")

    return CodemanifestConfig(usages=dict(usages), annotations=annotations)


def _require_mapping(data: dict, key: str) -> dict:
    """Extract a required mapping section, raising KeyError/ValueError as appropriate."""
    try:
        section = data[key]
    except KeyError as err:
        raise KeyError(f"{key} is required in .goga/config.yml") from err

    if not isinstance(section, dict):
        raise ValueError(f"'{key}' must be a mapping in .goga/config.yml")
    return section


def _parse_build(build_data: dict) -> BuildConfig:
    """Parse and validate the build section into a BuildConfig instance.

    Hard-rejects the deprecated `build.image` field (schema break).
    """
    if "image" in build_data:
        raise ValueError("build.image is no longer supported — set top-level 'image' in .goga/config.yml")

    try:
        task_executor_data = build_data["task_executor"]
    except KeyError as err:
        raise KeyError("build.task_executor is required in .goga/config.yml") from err

    if not isinstance(task_executor_data, dict):
        raise ValueError("build.task_executor must be a mapping in .goga/config.yml")

    task_executor = _parse_task_executor(task_executor_data)

    return BuildConfig(
        task_executor=task_executor,
        worktree=build_data.get("worktree"),
        skip_finalize=build_data.get("skip_finalize"),
        session_timeout=build_data.get("session_timeout"),
        idle_timeout=build_data.get("idle_timeout"),
        wait=build_data.get("wait"),
        max_iterations=build_data.get("max_iterations"),
        review_patience=build_data.get("review_patience"),
        prompts_dir=build_data.get("prompts_dir"),
        agents_dir=build_data.get("agents_dir"),
        codex_review=build_data.get("codex_review"),
    )


def load_config() -> Config:
    """Load project configuration from .goga/config.yml in the current working directory.

    Returns:
        Config instance with parsed top-level image, BuildConfig, PipelineConfig,
        and TaskExecutorConfig.

    Raises:
        FileNotFoundError: if .goga/config.yml does not exist or is empty.
        ValueError: if .goga/config.yml is not a YAML mapping or invalid field values,
            or when the deprecated build.image field is present.
        KeyError: if required sections are missing (language, build, build.task_executor,
            pipeline).
        yaml.YAMLError: if YAML parsing fails.
    """
    config_path = Path("./.goga/config.yml")

    if not config_path.exists():
        raise FileNotFoundError(".goga/config.yml not found in project root")

    with config_path.open() as f:
        data = yaml.safe_load(f)

    if data is None:
        raise FileNotFoundError(".goga/config.yml not found in project root")

    if not isinstance(data, dict):
        raise ValueError(".goga/config.yml must be a YAML mapping")

    lang = _parse_language(data)
    image = _parse_image(data)
    pipeline = _parse_pipeline(_require_mapping(data, "pipeline"))
    build = _parse_build(_require_mapping(data, "build"))

    commands = data.get("commands", {})
    if not isinstance(commands, dict):
        raise ValueError("'commands' must be a mapping in .goga/config.yml")
    commands = dict(commands)

    return Config(
        lang=lang,
        image=image,
        build=build,
        pipeline=pipeline,
        commands=commands,
        codemanifest=_parse_codemanifest(data),
    )

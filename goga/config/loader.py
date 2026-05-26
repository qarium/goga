# goga/config/loader.py — load_config function

from pathlib import Path

import yaml

from .config import BuildConfig, CodemanifestConfig, Config, TaskExecutor


def _parse_task_executor(task_executor_data: dict) -> TaskExecutor:
    """Parse and validate task_executor section into a TaskExecutor instance."""
    agent = task_executor_data.get("agent")
    if not isinstance(agent, str) or not agent.strip():
        raise ValueError("build.task_executor.agent is required in .goga/config.yml")

    env = task_executor_data.get("env", {})
    if not isinstance(env, dict):
        raise ValueError("build.task_executor.env must be a mapping in .goga/config.yml")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise ValueError("build.task_executor.env must have string keys and values")

    return TaskExecutor(agent=agent.strip(), env=dict(env))


def _parse_language(data: dict) -> str:
    """Extract and validate the language field from YAML data."""
    try:
        lang = data["language"]
    except KeyError as err:
        raise KeyError("language is required in .goga/config.yml") from err

    if not isinstance(lang, str) or not lang.strip():
        raise ValueError("language must be a non-empty string in .goga/config.yml")

    return lang.strip()


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


def load_config() -> Config:
    """Load project configuration from .goga/config.yml in the current working directory.

    Returns:
        Config instance with parsed BuildConfig and TaskExecutor.

    Raises:
        FileNotFoundError: if .goga/config.yml does not exist or is empty.
        ValueError: if .goga/config.yml is not a YAML mapping or invalid field values.
        KeyError: if required sections are missing (language, build, build.task_executor).
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
    commands = data.get("commands", {})

    try:
        build_data = data["build"]
    except KeyError as err:
        raise KeyError("build is required in .goga/config.yml") from err

    if not isinstance(build_data, dict):
        raise ValueError("'build' must be a mapping in .goga/config.yml")

    if not isinstance(commands, dict):
        raise ValueError("'commands' must be a mapping in .goga/config.yml")
    commands = dict(commands)

    try:
        task_executor_data = build_data["task_executor"]
    except KeyError as err:
        raise KeyError("build.task_executor is required in .goga/config.yml") from err

    if not isinstance(task_executor_data, dict):
        raise ValueError("build.task_executor must be a mapping in .goga/config.yml")

    task_executor = _parse_task_executor(task_executor_data)

    build = BuildConfig(
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

    return Config(lang=lang, build=build, commands=commands, codemanifest=_parse_codemanifest(data))

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


def _parse_proxy(proxy_data, section: str) -> str | None:
    """Validate an optional proxy field; None is a valid value."""
    if proxy_data is not None and not isinstance(proxy_data, str):
        raise ValueError(f"{section}.proxy must be a string in .goga/config.yml")
    return proxy_data


def _parse_hosts(hosts_data, section: str) -> dict[str, str]:
    """Validate an optional host→IP mapping; None/absent resolves to an empty dict."""
    if hosts_data is None:
        return {}
    if not isinstance(hosts_data, dict):
        raise ValueError(f"{section}.hosts must be a mapping in .goga/config.yml")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in hosts_data.items()):
        raise ValueError(f"{section}.hosts must have string keys and values in .goga/config.yml")
    return dict(hosts_data)


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

    proxy = _parse_proxy(pipeline_data.get("proxy"), "pipeline")
    hosts = _parse_hosts(pipeline_data.get("hosts"), "pipeline")

    return PipelineConfig(agent=agent.strip(), env=dict(env), proxy=proxy, hosts=hosts)


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


def _parse_dockerfile(data: dict) -> str | None:
    """Extract the optional top-level dockerfile field; None is a valid value.

    Mirrors `_parse_image`: a non-string value raises ValueError.
    """
    dockerfile = data.get("dockerfile")
    if dockerfile is not None and not isinstance(dockerfile, str):
        raise ValueError("dockerfile must be a string in .goga/config.yml")
    return dockerfile


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


def _parse_tools(data: dict) -> dict[str, str] | None:
    """Extract the optional top-level tools mapping.

    Structural-only extraction — performs NO semantic validation of value
    contents (operator-prefixed forms, malformed numerics, pre-release forms
    all pass through verbatim). The loader is not the validation authority for
    the version grammar; that responsibility belongs to the consumer.

    Returns None when the key is absent or YAML-null; an empty dict when the
    section is present but empty; a plain dict copy otherwise. YAML-null
    individual values ('viewer:') are a structural type error and raise
    ValueError — they are NOT coerced to 'latest'.
    """
    tools_data = data.get("tools")
    if tools_data is None:
        return None
    if not isinstance(tools_data, dict):
        raise ValueError("'tools' must be a mapping in .goga/config.yml")
    for k, v in tools_data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("'tools' must have string keys and values in .goga/config.yml")
    return dict(tools_data)


def _optional_mapping(data: dict, key: str) -> dict | None:
    """Extract an optional mapping section.

    Returns None when the key is absent (or explicitly null); raises ValueError
    when the key is present but not a mapping. The loader does not enforce
    presence of optional sections — that is the consuming command's responsibility.
    """
    section = data.get(key)
    if section is None:
        return None
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

    proxy = _parse_proxy(build_data.get("proxy"), "build")
    hosts = _parse_hosts(build_data.get("hosts"), "build")

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
        proxy=proxy,
        hosts=hosts,
    )


def load_config() -> Config:
    """Load project configuration from .goga/config.yml in the current working directory.

    Returns:
        Config instance. Top-level image and dockerfile are None-able; build and
        pipeline are None when their sections are absent in .goga/config.yml.

    Raises:
        FileNotFoundError: if .goga/config.yml does not exist or is empty.
        ValueError: if .goga/config.yml is not a YAML mapping or invalid field values,
            or when the deprecated build.image field is present.
        KeyError: if required sections are missing (language, or build.task_executor
            when build is present).
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
    dockerfile = _parse_dockerfile(data)
    pipeline_data = _optional_mapping(data, "pipeline")
    pipeline = _parse_pipeline(pipeline_data) if pipeline_data is not None else None
    build_data = _optional_mapping(data, "build")
    build = _parse_build(build_data) if build_data is not None else None

    commands = data.get("commands", {})
    if not isinstance(commands, dict):
        raise ValueError("'commands' must be a mapping in .goga/config.yml")
    commands = dict(commands)

    tools = _parse_tools(data)

    return Config(
        lang=lang,
        image=image,
        dockerfile=dockerfile,
        build=build,
        pipeline=pipeline,
        commands=commands,
        codemanifest=_parse_codemanifest(data),
        tools=tools,
    )
